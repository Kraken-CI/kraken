import { ComponentFixture, TestBed } from '@angular/core/testing'

import { TcrTableComponent } from './tcr-table.component'

describe('TcrTableComponent', () => {
    let component: TcrTableComponent
    let fixture: ComponentFixture<TcrTableComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [TcrTableComponent],
        }).compileComponents()
    })

    beforeEach(() => {
        fixture = TestBed.createComponent(TcrTableComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})

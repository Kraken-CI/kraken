import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { DiagsPageComponent } from './diags-page.component'

describe('DiagsPageComponent', () => {
    let component: DiagsPageComponent
    let fixture: ComponentFixture<DiagsPageComponent>

    beforeEach(waitForAsync(() => {
        TestBed.configureTestingModule({
            declarations: [DiagsPageComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(DiagsPageComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})

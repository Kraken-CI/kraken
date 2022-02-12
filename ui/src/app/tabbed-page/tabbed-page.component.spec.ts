import { ComponentFixture, TestBed } from '@angular/core/testing'

import { TabbedPageComponent } from './tabbed-page.component'

describe('TabbedPageComponent', () => {
    let component: TabbedPageComponent
    let fixture: ComponentFixture<TabbedPageComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [TabbedPageComponent],
        }).compileComponents()
    })

    beforeEach(() => {
        fixture = TestBed.createComponent(TabbedPageComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})

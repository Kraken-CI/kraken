import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { MainPageComponent } from './main-page.component'

describe('MainPageComponent', () => {
    let component: MainPageComponent
    let fixture: ComponentFixture<MainPageComponent>

    beforeEach(waitForAsync(() => {
        TestBed.configureTestingModule({
            declarations: [MainPageComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(MainPageComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
